import unittest
from pathlib import Path
import sys
from unittest import mock
import tempfile
import os


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress
from sentinel.server.services.repositories import TestResultRecord


class ProgressResolvedTargetsTest(unittest.TestCase):
    def tearDown(self):
        cache = getattr(progress, "_RESOLVED_TARGETS_CACHE", None)
        if isinstance(cache, dict):
            cache.clear()

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
            payload_by_path = {
                str(project_data_path): project_data_payload,
                str(resolved_path): resolved_payload,
            }

            with mock.patch.object(progress, "_latest_project_data_path", return_value=project_data_path):
                with mock.patch.object(progress, "_resolved_targets_path_for_project_data", return_value=resolved_path):
                    with mock.patch.object(progress, "_load_json", side_effect=lambda p: payload_by_path[str(p)]):
                        out = progress.commissioning_progress(projectId="p1", latest_results=latest_results)

            self.assertEqual(out["counts"]["totalTargets"], 1)
            self.assertEqual(out["counts"]["pass"], 1)

    def test_button_target_labels_include_graphics_bitmap_and_icon(self):
        btn = {
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {},
                "graphics": {"bitmap": True, "icon": True},
                "pageLink": False,
            }
        }
        labels = progress._button_target_labels(btn)
        self.assertIn("Bitmap", labels)
        self.assertIn("Icon", labels)

    def test_derive_device_targets_uses_scope_button_id_for_textless_bitmap_button(self):
        project_data = {
            "devices": [
                {
                    "diagnostics": {
                        "deviceId": 89,
                        "pages": [
                            {
                                "pageId": 353,
                                "buttons": [
                                    {
                                        "buttonId": 41392,
                                        "buttonTagName": None,
                                        "identifiers": {"text": ""},
                                    }
                                ],
                            }
                        ],
                    },
                    "userFacing": {
                        "displayName": "Entry KA11",
                        "pages": [
                            {
                                "layers": [
                                    {
                                        "buttonCategories": {
                                            "uiItems": [
                                                {
                                                    "buttonIdentity": {
                                                        "buttonTagName": None,
                                                        "text": "",
                                                        "buttonType": None,
                                                    },
                                                    "testTargets": {
                                                        "text": False,
                                                        "macros": False,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "graphics": {"bitmap": True, "icon": False},
                                                        "pageLink": False,
                                                    },
                                                    "apexScopeSource": {"button": {"buttonId": 41392}},
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ],
                    },
                }
            ]
        }

        rows = progress._derive_device_targets(project_data)
        self.assertEqual(len(rows), 1)
        expected = set(rows[0].get("expected") or set())
        self.assertIn("btn:89:353:41392:Bitmap", expected)

    def test_commissioning_progress_reuses_derived_targets_when_project_data_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data_path = td_path / "sample_project_data.json"
            project_data_path.write_text("{}", encoding="utf-8")
            latest_results = {}

            project_data_payload = {
                "devices": [
                    {
                        "userFacing": {"displayName": "Device A", "pages": []},
                        "diagnostics": {"deviceId": 81, "pages": []},
                    }
                ],
                "events": {"system": [], "driver": []},
            }
            event_targets = {"system": set(), "driver": set()}
            device_targets = [{"deviceId": 81, "displayName": "Device A", "expected": set()}]

            with mock.patch.object(progress, "_latest_project_data_path", return_value=project_data_path):
                with mock.patch.object(progress, "_resolved_targets_path_for_project_data", return_value=td_path / "missing.json"):
                    with mock.patch.object(progress, "_load_json", return_value=project_data_payload):
                        with mock.patch.object(progress, "_derive_event_section_targets", return_value=event_targets):
                            with mock.patch.object(progress, "_derive_device_targets", return_value=device_targets) as derive_mock:
                                progress.commissioning_progress(projectId="p1", latest_results=latest_results)
                                progress.commissioning_progress(projectId="p1", latest_results=latest_results)

            self.assertEqual(derive_mock.call_count, 1)

    def test_commissioning_progress_rebuilds_targets_when_project_data_mtime_changes(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            project_data_path = td_path / "sample_project_data.json"
            project_data_path.write_text("{}", encoding="utf-8")
            latest_results = {}

            project_data_payload = {
                "devices": [
                    {
                        "userFacing": {"displayName": "Device A", "pages": []},
                        "diagnostics": {"deviceId": 81, "pages": []},
                    }
                ],
                "events": {"system": [], "driver": []},
            }
            event_targets = {"system": set(), "driver": set()}
            device_targets = [{"deviceId": 81, "displayName": "Device A", "expected": set()}]

            with mock.patch.object(progress, "_latest_project_data_path", return_value=project_data_path):
                with mock.patch.object(progress, "_resolved_targets_path_for_project_data", return_value=td_path / "missing.json"):
                    with mock.patch.object(progress, "_load_json", return_value=project_data_payload):
                        with mock.patch.object(progress, "_derive_event_section_targets", return_value=event_targets):
                            with mock.patch.object(progress, "_derive_device_targets", return_value=device_targets) as derive_mock:
                                progress.commissioning_progress(projectId="p1", latest_results=latest_results)
                                project_data_path.write_text("{\"touch\":1}", encoding="utf-8")
                                current_mtime = project_data_path.stat().st_mtime_ns
                                os.utime(project_data_path, ns=(current_mtime + 2_000_000_000, current_mtime + 2_000_000_000))
                                progress.commissioning_progress(projectId="p1", latest_results=latest_results)

            self.assertEqual(derive_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
