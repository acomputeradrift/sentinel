import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.server.services.report_document import (
    PRESET_CLOSEOUT,
    PRESET_DEALER_PUNCH_LIST,
    PRESET_FULL_AUDIT,
    assemble_report_document,
    build_report_document,
    resolve_report_options,
)


def _sample_cover():
    return {
        "clientName": "Acme",
        "projectName": "Job One",
        "projectId": "proj-1",
        "originalFilename": "house.apex",
        "uploadedAtUtc": "2026-03-21T00:00:00Z",
        "status": "READY",
    }


def _sample_progress():
    return {
        "projectId": "proj-1",
        "counts": {
            "totalTargets": 4,
            "testedTargets": 3,
            "pass": 1,
            "fail": 2,
            "untested": 1,
            "percentComplete": 0.75,
        },
        "lastTestedAtUtc": "2026-03-21T02:00:00Z",
        "eventSections": {
            "system": {
                "counts": {
                    "totalTargets": 1,
                    "testedTargets": 1,
                    "pass": 1,
                    "fail": 0,
                    "untested": 0,
                    "percentComplete": 1.0,
                },
                "lastTestedAtUtc": "2026-03-21T01:00:00Z",
            },
            "driver": {
                "counts": {
                    "totalTargets": 1,
                    "testedTargets": 0,
                    "pass": 0,
                    "fail": 0,
                    "untested": 1,
                    "percentComplete": 0.0,
                },
                "lastTestedAtUtc": None,
            },
        },
        "devices": [
            {
                "deviceId": "dev-1",
                "displayName": "Keypad",
                "counts": {
                    "totalTargets": 1,
                    "testedTargets": 1,
                    "pass": 0,
                    "fail": 1,
                    "untested": 0,
                    "percentComplete": 1.0,
                },
                "lastTestedAtUtc": "2026-03-21T02:00:00Z",
            },
            {
                "deviceId": "dev-2",
                "displayName": "Touch",
                "counts": {
                    "totalTargets": 1,
                    "testedTargets": 1,
                    "pass": 0,
                    "fail": 1,
                    "untested": 0,
                    "percentComplete": 1.0,
                },
                "lastTestedAtUtc": "2026-03-21T01:30:00Z",
            },
        ],
    }


def _sample_fails():
    return [
        {
            "targetKey": "btn:1:2:3:Lights",
            "currentOutcome": "FAIL",
            "lastFailNote": "No voltage",
            "deviceName": "Keypad",
            "pageName": "Home",
            "buttonName": "Lights",
            "effectiveRoomName": "Kitchen",
            "effectiveSourceName": None,
            "techName": "Alex",
            "tag": "IN_PROGRESS",
            "deviceId": "dev-1",
        },
        {
            "targetKey": "btn:2:2:9:Shade",
            "currentOutcome": "FAIL",
            "lastFailNote": "Stuck",
            "deviceName": "Touch",
            "pageName": "Shades",
            "buttonName": "Shade",
            "effectiveRoomName": "Theater",
            "effectiveSourceName": None,
            "techName": "Alex",
            "tag": "NOT_STARTED",
            "deviceId": "dev-2",
        },
    ]


def _sample_current_targets():
    return [
        {
            "targetKey": "btn:1:2:3:Lights",
            "kind": "BUTTON",
            "targetName": "Lights",
            "currentOutcome": "FAIL",
            "lastTestedAtUtc": "2026-03-21T02:00:00Z",
            "lastFailNote": "No voltage",
            "techName": "Alex",
            "deviceId": "dev-1",
            "eventSection": None,
        },
        {
            "targetKey": "event:10:Trigger",
            "kind": "EVENT",
            "targetName": "Trigger",
            "currentOutcome": "PASS",
            "lastTestedAtUtc": "2026-03-21T01:00:00Z",
            "lastFailNote": None,
            "techName": "Alex",
            "deviceId": None,
            "eventSection": "system",
        },
        {
            "targetKey": "event:11:Trigger",
            "kind": "EVENT",
            "targetName": "Trigger",
            "currentOutcome": "UNTESTED",
            "lastTestedAtUtc": None,
            "lastFailNote": None,
            "techName": None,
            "deviceId": None,
            "eventSection": "driver",
        },
    ]


def _sample_history(*, count: int = 3, include_prior: bool = True):
    rows = []
    if include_prior:
        rows.append(
            {
                "testResultId": "old-1",
                "recordedAtUtc": "2026-03-20T00:00:00Z",
                "outcome": "FAIL",
                "failNote": "old fail",
                "source": "SINGLE",
                "batchId": None,
                "targetKey": "btn:1:2:3:Lights",
                "techName": "Alex",
                "passBoundary": "prior",
            }
        )
    for i in range(count):
        rows.append(
            {
                "testResultId": f"cur-{i}",
                "recordedAtUtc": f"2026-03-21T01:{i:02d}:00Z",
                "outcome": "PASS" if i % 2 == 0 else "FAIL",
                "failNote": None if i % 2 == 0 else f"note {i}",
                "source": "GROUP" if i == 1 else "SINGLE",
                "batchId": "batch-1" if i == 1 else None,
                "targetKey": f"btn:1:2:{i}:T",
                "techName": "Alex",
                "passBoundary": "current",
            }
        )
    return rows


def _sample_source(**overrides):
    source = {
        "cover": _sample_cover(),
        "progress": _sample_progress(),
        "fails": _sample_fails(),
        "currentTargets": _sample_current_targets(),
        "history": _sample_history(count=3),
        "testingTypes": {
            "types": [
                {"id": "button:Text", "label": "Text", "enabled": True},
                {"id": "button:Bitmap", "label": "Bitmap", "enabled": False},
            ]
        },
        "technicianNames": ["Alex", "Sam"],
        "currentPassStartedAtUtc": "2026-03-21T00:30:00Z",
    }
    source.update(overrides)
    return source


class ReportOptionsTest(unittest.TestCase):
    def test_closeout_preset_defaults(self):
        opts = resolve_report_options({"preset": PRESET_CLOSEOUT})
        self.assertEqual(opts["preset"], PRESET_CLOSEOUT)
        include = opts["include"]
        self.assertTrue(include["cover"])
        self.assertTrue(include["progressSummary"])
        self.assertTrue(include["deviceCounts"])
        self.assertTrue(include["failDetail"])
        self.assertFalse(include["eventSectionCounts"])
        self.assertFalse(include["currentTargets"])
        self.assertFalse(include["programmerFields"])
        self.assertFalse(include["fullHistory"])
        self.assertFalse(include["includePriorPasses"])
        self.assertFalse(include["testingTypeLegend"])
        self.assertFalse(include["operatorAppendix"])

    def test_dealer_punch_list_preset_defaults(self):
        opts = resolve_report_options({"preset": PRESET_DEALER_PUNCH_LIST})
        include = opts["include"]
        self.assertTrue(include["cover"])
        self.assertTrue(include["failDetail"])
        self.assertTrue(include["programmerFields"])
        self.assertFalse(include["progressSummary"])
        self.assertFalse(include["deviceCounts"])
        self.assertFalse(include["fullHistory"])
        self.assertFalse(include["operatorAppendix"])

    def test_full_audit_preset_defaults(self):
        opts = resolve_report_options({"preset": PRESET_FULL_AUDIT})
        include = opts["include"]
        self.assertTrue(include["cover"])
        self.assertTrue(include["progressSummary"])
        self.assertTrue(include["eventSectionCounts"])
        self.assertTrue(include["deviceCounts"])
        self.assertTrue(include["currentTargets"])
        self.assertEqual(include["currentTargetOutcomes"], ["PASS", "FAIL", "UNTESTED"])
        self.assertTrue(include["failDetail"])
        self.assertTrue(include["programmerFields"])
        self.assertTrue(include["fullHistory"])
        self.assertTrue(include["includePriorPasses"])
        self.assertTrue(include["testingTypeLegend"])
        self.assertFalse(include["operatorAppendix"])

    def test_overrides_replace_preset_sections(self):
        opts = resolve_report_options(
            {
                "preset": PRESET_CLOSEOUT,
                "include": {"fullHistory": True, "operatorAppendix": True, "progressSummary": False},
            }
        )
        self.assertTrue(opts["include"]["fullHistory"])
        self.assertTrue(opts["include"]["operatorAppendix"])
        self.assertFalse(opts["include"]["progressSummary"])
        self.assertTrue(opts["include"]["failDetail"])

    def test_closeout_document_omits_audit_and_tokens(self):
        doc = assemble_report_document(
            options=resolve_report_options({"preset": PRESET_CLOSEOUT}),
            source=_sample_source(),
        )
        self.assertIn("cover", doc)
        self.assertEqual(doc["cover"]["clientName"], "Acme")
        self.assertIn("progressSummary", doc)
        self.assertIn("deviceCounts", doc)
        self.assertIn("failDetail", doc)
        self.assertEqual(doc["failDetail"][0]["lastFailNote"], "No voltage")
        self.assertNotIn("tag", doc["failDetail"][0])
        self.assertNotIn("eventSectionCounts", doc)
        self.assertNotIn("currentTargets", doc)
        self.assertNotIn("history", doc)
        self.assertNotIn("testingTypeLegend", doc)
        self.assertNotIn("operatorAppendix", doc)
        blob = str(doc)
        self.assertNotIn("/testing/", blob)
        self.assertNotIn("token-", blob)

    def test_punch_list_has_fails_with_programmer_fields(self):
        doc = assemble_report_document(
            options=resolve_report_options({"preset": PRESET_DEALER_PUNCH_LIST}),
            source=_sample_source(),
        )
        self.assertIn("cover", doc)
        self.assertIn("failDetail", doc)
        row = doc["failDetail"][0]
        self.assertEqual(row["lastFailNote"], "No voltage")
        self.assertEqual(row["deviceName"], "Keypad")
        self.assertEqual(row["pageName"], "Home")
        self.assertEqual(row["buttonName"], "Lights")
        self.assertEqual(row["effectiveRoomName"], "Kitchen")
        self.assertEqual(row["techName"], "Alex")
        self.assertEqual(row["tag"], "IN_PROGRESS")
        self.assertNotIn("progressSummary", doc)
        self.assertNotIn("history", doc)

    def test_full_audit_includes_uncapped_history(self):
        history = _sample_history(count=60, include_prior=True)
        self.assertGreater(len(history), 50)
        doc = assemble_report_document(
            options=resolve_report_options({"preset": PRESET_FULL_AUDIT}),
            source=_sample_source(history=history),
        )
        self.assertIn("currentTargets", doc)
        self.assertEqual(len(doc["currentTargets"]), 3)
        self.assertIn("history", doc)
        self.assertEqual(len(doc["history"]), len(history))
        self.assertTrue(any(row.get("source") == "GROUP" for row in doc["history"]))
        self.assertTrue(any(row.get("techName") == "Alex" for row in doc["history"]))
        self.assertIn("testingTypeLegend", doc)

    def test_history_without_prior_passes_drops_old_rows(self):
        opts = resolve_report_options({"preset": PRESET_FULL_AUDIT, "include": {"includePriorPasses": False}})
        doc = assemble_report_document(options=opts, source=_sample_source())
        keys = [row["testResultId"] for row in doc["history"]]
        self.assertNotIn("old-1", keys)
        self.assertTrue(all(k.startswith("cur-") for k in keys))

    def test_device_scope_filters_devices_and_fails(self):
        opts = resolve_report_options(
            {
                "preset": PRESET_CLOSEOUT,
                "scope": {"deviceIds": ["dev-1"], "includeSystemEvents": False, "includeDriverEvents": False},
            }
        )
        doc = assemble_report_document(options=opts, source=_sample_source())
        self.assertEqual([d["deviceId"] for d in doc["deviceCounts"]], ["dev-1"])
        self.assertEqual([f["targetKey"] for f in doc["failDetail"]], ["btn:1:2:3:Lights"])

    def test_operator_appendix_is_names_only(self):
        opts = resolve_report_options({"preset": PRESET_CLOSEOUT, "include": {"operatorAppendix": True}})
        doc = assemble_report_document(options=opts, source=_sample_source())
        self.assertEqual(doc["operatorAppendix"]["technicianNames"], ["Alex", "Sam"])
        self.assertNotIn("techUrl", doc["operatorAppendix"])
        self.assertNotIn("tokens", doc["operatorAppendix"])

    def test_build_report_document_uses_full_history_not_activity_cap(self):
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId="jamie", name="Acme")
        project = repo.create_project(userId="jamie", clientId=client.clientId, name="Job One")
        _link, tok = repo.create_tech_link(projectId=project.projectId, label="Alex")
        for i in range(55):
            repo.append_test_result(
                techToken=tok.techToken,
                target={
                    "targetKey": f"btn:1:2:{i}:T{i}",
                    "kind": "BUTTON",
                    "targetName": f"T{i}",
                    "refs": {"deviceName": "Keypad", "pageName": "Home", "buttonName": f"T{i}"},
                },
                outcome="PASS" if i % 2 == 0 else "FAIL",
                failNote=None if i % 2 == 0 else f"note {i}",
            )
        doc = build_report_document(
            repo=repo,
            projectId=project.projectId,
            options=resolve_report_options({"preset": PRESET_FULL_AUDIT}),
        )
        self.assertEqual(len(doc["history"]), 55)
        self.assertTrue(all("techUrl" not in row for row in doc["history"]))
        self.assertEqual(doc["cover"]["clientName"], "Acme")
        self.assertEqual(doc["cover"]["projectName"], "Job One")


if __name__ == "__main__":
    unittest.main()
