import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACT = ROOT / "src" / "sentinel" / "extraction" / "extract_project_data.py"
GENERATE = ROOT / "src" / "sentinel" / "generation" / "generate_html.py"
PROJECT_STRUCTURE = ROOT / "src" / "sentinel" / "contracts" / "apex_project_structure_v4.json"
APP_UI = ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json"


class GenerationResolvedArtifactParityTest(unittest.TestCase):
    def test_generation_output_matches_with_or_without_resolved_artifact(self):
        from dev_tests.integration.test_scripts import create_test_apex

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            apex_path = td_path / "sample.apex"
            create_test_apex(apex_path)

            extract_out = td_path / "extract"
            extract_out.mkdir(parents=True, exist_ok=True)
            run_extract = subprocess.run(
                [
                    sys.executable,
                    str(EXTRACT),
                    "--apex",
                    str(apex_path),
                    "--project-structure",
                    str(PROJECT_STRUCTURE),
                    "--out-dir",
                    str(extract_out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_extract.returncode, 0, msg=run_extract.stdout + "\n" + run_extract.stderr)

            project_data = extract_out / "sample_project_data.json"
            resolved = extract_out / "sample_resolved_targets.json"
            self.assertTrue(project_data.exists())
            self.assertTrue(resolved.exists())

            without_artifact_out = td_path / "without-artifact"
            with_artifact_out = td_path / "with-artifact"
            without_artifact_out.mkdir(parents=True, exist_ok=True)
            with_artifact_out.mkdir(parents=True, exist_ok=True)

            run_without = subprocess.run(
                [
                    sys.executable,
                    str(GENERATE),
                    "--project-data",
                    str(project_data),
                    "--app-ui",
                    str(APP_UI),
                    "--out-dir",
                    str(without_artifact_out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_without.returncode, 0, msg=run_without.stdout + "\n" + run_without.stderr)

            run_with = subprocess.run(
                [
                    sys.executable,
                    str(GENERATE),
                    "--project-data",
                    str(project_data),
                    "--resolved-targets",
                    str(resolved),
                    "--app-ui",
                    str(APP_UI),
                    "--out-dir",
                    str(with_artifact_out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(run_with.returncode, 0, msg=run_with.stdout + "\n" + run_with.stderr)

            without_files = sorted([p.name for p in without_artifact_out.iterdir() if p.is_file()])
            with_files = sorted([p.name for p in with_artifact_out.iterdir() if p.is_file()])
            self.assertEqual(without_files, with_files)

            for name in without_files:
                left = (without_artifact_out / name).read_text(encoding="utf-8")
                right = (with_artifact_out / name).read_text(encoding="utf-8")
                self.assertEqual(left, right, msg=f"Output mismatch for {name}")


if __name__ == "__main__":
    unittest.main()

