import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "src" / "sentinel" / "extraction" / "extract_project_data.py"
PROJECT_STRUCTURE = ROOT / "src" / "sentinel" / "contracts" / "apex_project_structure_v4.json"


def _write_test_apex(path: Path) -> None:
    from dev_tests.integration.test_scripts import create_test_apex

    create_test_apex(path)


class ExtractionResolvedArtifactTest(unittest.TestCase):
    def test_extract_writes_resolved_targets_artifact_and_keeps_project_data_clean(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex_path = td_path / "sample.apex"
            _write_test_apex(apex_path)

            run = subprocess.run(
                [
                    sys.executable,
                    str(EXTRACT),
                    "--apex",
                    str(apex_path),
                    "--project-structure",
                    str(PROJECT_STRUCTURE),
                    "--out-dir",
                    str(td_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, msg=run.stdout + "\n" + run.stderr)

            project_data_path = td_path / "sample_project_data.json"
            resolved_path = td_path / "sample_resolved_targets.json"
            self.assertTrue(project_data_path.exists())
            self.assertTrue(resolved_path.exists())

            project_data = json.loads(project_data_path.read_text(encoding="utf-8"))
            self.assertNotIn("resolvedTargets", project_data)
            user_layers: list[dict] = []
            for device in project_data.get("devices", []):
                user = device.get("userFacing", {}) if isinstance(device, dict) else {}
                pages = user.get("pages", []) if isinstance(user, dict) else []
                if not isinstance(pages, list):
                    continue
                for page in pages:
                    if not isinstance(page, dict):
                        continue
                    layers = page.get("layers", [])
                    if not isinstance(layers, list):
                        continue
                    for layer in layers:
                        if isinstance(layer, dict):
                            user_layers.append(layer)
            self.assertGreater(len(user_layers), 0)
            for layer in user_layers:
                self.assertIn("sharedLayerId", layer)
                self.assertIsInstance(layer["sharedLayerId"], int)

            resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
            self.assertEqual(resolved.get("format"), "sentinel-resolved-targets-v1")
            self.assertIn("devices", resolved)
            self.assertIn("events", resolved)

    def test_resolved_targets_artifact_is_deterministic_for_same_input(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex_path = td_path / "sample.apex"
            _write_test_apex(apex_path)

            for out_dir_name in ("out1", "out2"):
                out_dir = td_path / out_dir_name
                out_dir.mkdir(parents=True, exist_ok=True)
                run = subprocess.run(
                    [
                        sys.executable,
                        str(EXTRACT),
                        "--apex",
                        str(apex_path),
                        "--project-structure",
                        str(PROJECT_STRUCTURE),
                        "--out-dir",
                        str(out_dir),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(run.returncode, 0, msg=run.stdout + "\n" + run.stderr)

            one = json.loads((td_path / "out1" / "sample_resolved_targets.json").read_text(encoding="utf-8"))
            two = json.loads((td_path / "out2" / "sample_resolved_targets.json").read_text(encoding="utf-8"))
            self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()

