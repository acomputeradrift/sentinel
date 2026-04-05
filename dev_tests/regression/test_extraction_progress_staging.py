import unittest
from pathlib import Path
import sys
import io
import json
import tempfile
from contextlib import redirect_stdout
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.extraction.extractor_core import _map_staged_progress
from sentinel.extraction import extract_project_data as extract_script


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
            self.assertIn("SENTINEL_PROGRESS EXTRACTING 99.00", progress_lines)
            self.assertIn("SENTINEL_PROGRESS EXTRACTING 100.00", progress_lines)


if __name__ == "__main__":
    unittest.main()
