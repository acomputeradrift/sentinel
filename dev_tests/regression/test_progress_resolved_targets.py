import unittest
from pathlib import Path
import sys
from unittest import mock
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress
from sentinel.server.services.repositories import TestResultRecord


class ProgressResolvedTargetsTest(unittest.TestCase):
    def test_commissioning_progress_uses_resolved_targets_when_available(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data_path = td_path / "sample_project_data.json"
            resolved_path = td_path / "sample_resolved_targets.json"
            project_data_path.write_text("{}", encoding="utf-8")
            resolved_path.write_text("{}", encoding="utf-8")
            latest_results = {
                "tt2:2:ROOM:23:74:20:macro:3122:Macro": TestResultRecord(
                    testResultId="1",
                    projectId="p1",
                    recordedAtUtc="2026-01-01T00:00:00+00:00",
                    recordedBy={},
                    target={"targetKey": "tt2:2:ROOM:23:74:20:macro:3122:Macro"},
                    outcome="PASS",
                    failNote=None,
                )
            }

            project_data_payload = {
                "devices": [
                    {
                        "userFacing": {"displayName": "Device A", "pages": []},
                        "diagnostics": {"deviceId": 81, "pages": []},
                    }
                ],
                "events": {"system": [], "driver": []},
            }
            resolved_payload = {
                "format": "sentinel-resolved-targets-v1",
                "events": {"system": [], "driver": []},
                "devices": [
                    {
                        "deviceId": 81,
                        "displayName": "Device A",
                        "expected": ["tt2:2:ROOM:23:74:20:macro:3122:Macro"],
                    }
                ],
            }

            with mock.patch.object(progress, "_latest_project_data_path", return_value=project_data_path):
                with mock.patch.object(progress, "_resolved_targets_path_for_project_data", return_value=resolved_path):
                    with mock.patch.object(progress, "_load_json", side_effect=[project_data_payload, resolved_payload]):
                        out = progress.commissioning_progress(projectId="p1", latest_results=latest_results)

            self.assertEqual(out["counts"]["totalTargets"], 1)
            self.assertEqual(out["counts"]["pass"], 1)


if __name__ == "__main__":
    unittest.main()
