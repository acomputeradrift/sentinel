import os
import tempfile
import unittest
import io
import threading
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
    def test_subprocess_failure_message_is_tail_limited_for_large_output(self):
        from sentinel.server.services import pipeline

        class _FakeProc:
            def __init__(self):
                lines = [f"log-line-{idx}\n" for idx in range(1, 151)]
                self.stdout = io.StringIO("".join(lines))
                self.stderr = io.StringIO("boom-stderr")

            def wait(self):
                return 1

        with mock.patch.object(pipeline.subprocess, "Popen", return_value=_FakeProc()):
            with self.assertRaises(Exception) as raised:
                pipeline._run_subprocess_with_progress(
                    args=["dummy"],
                    cwd=Path("."),
                    env={},
                )
        text = str(raised.exception)
        self.assertIn("stdout_tail", text)
        self.assertIn("stdout_lines=", text)
        self.assertNotIn("\nlog-line-1\n", f"\n{text}\n")
        self.assertIn("log-line-150", text)

    def test_regenerate_rejects_parallel_run_for_same_project(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.services import pipeline

            project_id = "proj-lock"
            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex")
            started = threading.Event()
            release = threading.Event()

            def _fake_run(*, args, cwd, env, phase_hook=None):
                out_idx = args.index("--out-dir")
                stage_dir = Path(args[out_idx + 1])
                script = Path(args[1]).name
                if script == "extract_project_data.py":
                    started.set()
                    release.wait(timeout=3)
                    (stage_dir / "sample_project_data.json").write_text("{}", encoding="utf-8")
                elif script == "generate_html.py":
                    (stage_dir / "sample_project_data__project-home.html").write_text("<html></html>", encoding="utf-8")
                return "", ""

            first_result: dict[str, object] = {}
            first_error: list[Exception] = []

            def _run_first():
                try:
                    first_result.update(pipeline.regenerate_project(projectId=project_id, apex_path=apex_path))
                except Exception as exc:  # pragma: no cover - debugging path
                    first_error.append(exc)

            worker = threading.Thread(target=_run_first, daemon=True)
            with mock.patch.object(pipeline, "_run_subprocess_with_progress", side_effect=_fake_run):
                worker.start()
                self.assertTrue(started.wait(timeout=2), "First regenerate did not start in time.")
                with self.assertRaises(RuntimeError) as raised:
                    pipeline.regenerate_project(projectId=project_id, apex_path=apex_path)
                self.assertIn("already in progress", str(raised.exception))
                release.set()
                worker.join(timeout=3)

            self.assertFalse(worker.is_alive(), "First regenerate thread should complete after release.")
            self.assertFalse(first_error, f"First regenerate failed unexpectedly: {first_error}")
            self.assertEqual(first_result.get("projectId"), project_id)

    def test_subprocess_progress_parser_accepts_fractional_percent(self):
        from sentinel.server.services import pipeline

        class _FakeProc:
            def __init__(self):
                self.stdout = io.StringIO("SENTINEL_PROGRESS EXTRACTING 20.75\n")
                self.stderr = io.StringIO("")

            def wait(self):
                return 0

        captured: list[tuple[str, float]] = []
        with mock.patch.object(pipeline.subprocess, "Popen", return_value=_FakeProc()):
            out, err = pipeline._run_subprocess_with_progress(
                args=["dummy"],
                cwd=Path("."),
                env={},
                phase_hook=lambda phase, percent=0: captured.append((str(phase), float(percent))),
            )
        self.assertEqual(out.strip(), "SENTINEL_PROGRESS EXTRACTING 20.75")
        self.assertEqual(err, "")
        self.assertEqual(captured, [("extracting", 20.75)])

    def test_pipeline_returns_extract_generate_total_timings(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.services import pipeline

            project_id = "proj-time"
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
                return "", ""

            perf_samples = iter([100.0, 100.1, 101.35, 101.4, 104.15, 105.5])
            with mock.patch.object(pipeline, "_run_subprocess_with_progress", side_effect=_fake_run):
                with mock.patch.object(pipeline.time, "perf_counter", side_effect=lambda: next(perf_samples)):
                    out = pipeline.regenerate_project(projectId=project_id, apex_path=apex_path)

            timings = out.get("timings") if isinstance(out, dict) else None
            self.assertIsInstance(timings, dict)
            assert isinstance(timings, dict)
            self.assertAlmostEqual(float(timings.get("extractSec") or 0.0), 1.25, places=3)
            self.assertAlmostEqual(float(timings.get("generateSec") or 0.0), 2.75, places=3)
            self.assertAlmostEqual(float(timings.get("totalSec") or 0.0), 5.5, places=3)

    def test_pipeline_uses_v3_project_structure_contract(self):
        pipeline_file = ROOT / "src" / "sentinel" / "server" / "services" / "pipeline.py"
        text = pipeline_file.read_text(encoding="utf-8")
        self.assertIn("apex_project_structure_v4.json", text)

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
        self.assertIn("Extracting (", text)
        self.assertIn("Generating (", text)
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
                    phase_hook("extracting", 10.25)
                    phase_hook("extracting", 99.75)
                    phase_hook("generating", 50.5)
                    phase_hook("generating", 100.0)
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
            self.assertEqual(percents, [10.25, 99.75, 50.5, 100.0, 100])

    def test_upload_and_regenerate_logs_timing_baseline_with_upload_context(self):
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

            def _fake_regenerate(*, projectId: str, apex_path: Path, phase_hook=None):
                if callable(phase_hook):
                    phase_hook("extracting", 100)
                    phase_hook("generating", 100)
                return {
                    "projectId": projectId,
                    "outDir": str(Path(td) / "generated" / projectId),
                    "projectData": "x.json",
                    "timings": {"extractSec": 1.0, "generateSec": 2.0, "totalSec": 3.0},
                }

            with apex_path.open("rb") as f:
                with mock.patch.object(commissioning_api.pipeline, "regenerate_project", side_effect=_fake_regenerate):
                    with mock.patch.object(commissioning_api.log, "info") as log_info:
                        resp = client.post(
                            f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                            files={"apex": ("sample.apex", f, "application/octet-stream")},
                        )

            self.assertEqual(resp.status_code, 200)
            rendered = " ".join(str(call.args[0]) for call in log_info.call_args_list if call.args)
            self.assertIn("REGEN_BASELINE", rendered)

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
