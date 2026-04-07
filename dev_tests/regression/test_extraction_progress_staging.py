import unittest
from pathlib import Path
import sys
import io
import json
import tempfile
import time
from contextlib import redirect_stdout
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.extraction.extractor_core import _map_staged_progress
from sentinel.extraction import extract_project_data as extract_script
from sentinel.generation import generate_html as generate_script


class ExtractionProgressStagingTest(unittest.TestCase):
    def test_staged_progress_ranges(self):
        self.assertEqual(_map_staged_progress("setup", 0), 0)
        self.assertEqual(_map_staged_progress("setup", 100), 15)
        self.assertEqual(_map_staged_progress("work", 0), 15)
        self.assertEqual(_map_staged_progress("work", 100), 92)
        self.assertEqual(_map_staged_progress("finalize", 0), 92)
        self.assertEqual(_map_staged_progress("finalize", 100), 100)

    def test_staged_progress_preserves_fractional_resolution(self):
        a = float(_map_staged_progress("work", 10.11))
        b = float(_map_staged_progress("work", 10.19))
        self.assertGreater(b, a)

    def test_extract_script_emits_finalize_heartbeats_before_complete(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            apex_path = tmp / "sample.apex"
            contract_path = tmp / "apex_project_structure_v4.json"
            out_dir = tmp / "out"
            apex_path.write_bytes(b"sqlite-placeholder")
            contract_path.write_text(json.dumps({}), encoding="utf-8")

            fake_payload = {"events": {"system": [], "driver": []}, "devices": []}
            argv = [
                "extract_project_data.py",
                "--apex",
                str(apex_path),
                "--project-structure",
                str(contract_path),
                "--out-dir",
                str(out_dir),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(extract_script, "extract_project_data", return_value=fake_payload),
                mock.patch.object(extract_script, "validate_contract_shape", return_value=None),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = extract_script.main()

            self.assertEqual(rc, 0)
            progress_lines = [line.strip() for line in buf.getvalue().splitlines() if "SENTINEL_PROGRESS EXTRACTING" in line]
            values = [float(line.split("SENTINEL_PROGRESS EXTRACTING ", 1)[1]) for line in progress_lines]
            self.assertIn(99.0, values)
            self.assertIn(100.0, values)

    def test_extract_script_does_not_emit_synthetic_ticks_during_slow_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            apex_path = tmp / "sample.apex"
            contract_path = tmp / "apex_project_structure_v4.json"
            out_dir = tmp / "out"
            apex_path.write_bytes(b"sqlite-placeholder")
            contract_path.write_text(json.dumps({}), encoding="utf-8")

            fake_payload = {"events": {"system": [], "driver": []}, "devices": []}
            argv = [
                "extract_project_data.py",
                "--apex",
                str(apex_path),
                "--project-structure",
                str(contract_path),
                "--out-dir",
                str(out_dir),
            ]

            def _slow_extract(*args, **kwargs):
                _ = args, kwargs
                time.sleep(4.2)
                return fake_payload

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(extract_script, "extract_project_data", side_effect=_slow_extract),
                mock.patch.object(extract_script, "validate_contract_shape", return_value=None),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = extract_script.main()

            self.assertEqual(rc, 0)
            progress_lines = [line.strip() for line in buf.getvalue().splitlines() if "SENTINEL_PROGRESS EXTRACTING" in line]
            values = [float(line.split("SENTINEL_PROGRESS EXTRACTING ", 1)[1]) for line in progress_lines]
            pre_99 = [v for v in values if v < 99.0]
            self.assertEqual(len(pre_99), 0)

    def test_extract_script_emits_intermediate_finalize_progress(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            apex_path = tmp / "sample.apex"
            contract_path = tmp / "apex_project_structure_v4.json"
            out_dir = tmp / "out"
            apex_path.write_bytes(b"sqlite-placeholder")
            contract_path.write_text(json.dumps({}), encoding="utf-8")

            large_values = ["x" * 1024 for _ in range(1500)]
            fake_payload = {"events": {"system": [], "driver": []}, "devices": [{"blob": large_values}]}
            argv = [
                "extract_project_data.py",
                "--apex",
                str(apex_path),
                "--project-structure",
                str(contract_path),
                "--out-dir",
                str(out_dir),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(extract_script, "extract_project_data", return_value=fake_payload),
                mock.patch.object(extract_script, "validate_contract_shape", return_value=None),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = extract_script.main()

            self.assertEqual(rc, 0)
            progress_lines = [line.strip() for line in buf.getvalue().splitlines() if "SENTINEL_PROGRESS EXTRACTING" in line]
            values = [float(line.split("SENTINEL_PROGRESS EXTRACTING ", 1)[1]) for line in progress_lines]
            near_done = [v for v in values if 99.0 < v < 100.0]
            self.assertGreaterEqual(len(near_done), 3)

    def test_extract_script_logs_large_input_context(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            apex_path = tmp / "sample.apex"
            contract_path = tmp / "apex_project_structure_v4.json"
            out_dir = tmp / "out"
            apex_path.write_bytes(b"x" * 1234)
            contract_path.write_text("{}", encoding="utf-8")

            fake_payload = {"events": {"system": [], "driver": []}, "devices": []}
            argv = [
                "extract_project_data.py",
                "--apex",
                str(apex_path),
                "--project-structure",
                str(contract_path),
                "--out-dir",
                str(out_dir),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(extract_script, "extract_project_data", return_value=fake_payload),
                mock.patch.object(extract_script, "validate_contract_shape", return_value=None),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = extract_script.main()

            self.assertEqual(rc, 0)
            text = buf.getvalue()
            self.assertIn("apex_size_bytes=1234", text)
            self.assertIn("contract_size_bytes=2", text)

    def test_generate_script_logs_large_input_and_output_context(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            project_path = tmp / "sample_project_data.json"
            ui_path = tmp / "app_ui_structure.json"
            out_dir = tmp / "out"
            project_path.write_text("{}", encoding="utf-8")
            ui_path.write_text("{}", encoding="utf-8")

            fake_project = {"devices": [{"userFacing": {"displayName": "Device A", "pages": [{"pageName": "Home"}]}}]}
            fake_ui = {}
            argv = [
                "generate_html.py",
                "--project-data",
                str(project_path),
                "--app-ui",
                str(ui_path),
                "--out-dir",
                str(out_dir),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(generate_script, "load_json", side_effect=[fake_project, fake_ui]),
                mock.patch.object(generate_script, "render_project_home_html", return_value="<html></html>"),
                mock.patch.object(generate_script, "build_project_manifest", return_value={"devices": []}),
                mock.patch.object(
                    generate_script,
                    "build_device_render_bundle",
                    return_value={"html": "<html></html>", "payload": {"x": 1}},
                ),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = generate_script.main()

            self.assertEqual(rc, 0)
            text = buf.getvalue()
            self.assertIn("project_data_size_bytes=2", text)
            self.assertIn("app_ui_size_bytes=2", text)
            self.assertIn("renderable_devices=1", text)
            self.assertIn("total_units=4", text)

    def test_generate_script_uses_shared_device_bundle_once_per_device(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            project_path = tmp / "sample_project_data.json"
            ui_path = tmp / "app_ui_structure.json"
            out_dir = tmp / "out"
            project_path.write_text("{}", encoding="utf-8")
            ui_path.write_text("{}", encoding="utf-8")

            fake_project = {"devices": [{"userFacing": {"displayName": "Device A", "pages": [{"pageName": "Home"}]}}]}
            fake_ui = {}
            argv = [
                "generate_html.py",
                "--project-data",
                str(project_path),
                "--app-ui",
                str(ui_path),
                "--out-dir",
                str(out_dir),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(generate_script, "load_json", side_effect=[fake_project, fake_ui]),
                mock.patch.object(generate_script, "render_project_home_html", return_value="<html></html>"),
                mock.patch.object(generate_script, "build_project_manifest", return_value={"devices": []}),
                mock.patch.object(
                    generate_script,
                    "build_device_render_bundle",
                    return_value={"html": "<html>device</html>", "payload": {"k": "v"}},
                ) as build_bundle,
            ):
                rc = generate_script.main()

            self.assertEqual(rc, 0)
            self.assertEqual(build_bundle.call_count, 1)


if __name__ == "__main__":
    unittest.main()
