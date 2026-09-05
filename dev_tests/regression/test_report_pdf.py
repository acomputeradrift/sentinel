import re
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from sentinel.server.services.report_document import (
    PRESET_CLOSEOUT,
    PRESET_FULL_AUDIT,
    assemble_report_document,
    resolve_report_options,
)
from sentinel.server.services.report_pdf import extract_pdf_text, render_report_pdf, report_download_filename


def _sample_doc(*, preset: str, **include_overrides):
    payload = {"preset": preset, "include": include_overrides} if include_overrides else {"preset": preset}
    return assemble_report_document(
        options=resolve_report_options(payload),
        source={
            "cover": {
                "clientName": "Acme",
                "projectName": "Job One",
                "projectId": "proj-1",
                "originalFilename": "house.apex",
                "uploadedAtUtc": "2026-03-21T00:00:00Z",
                "status": "READY",
            },
            "progress": {
                "counts": {
                    "totalTargets": 2,
                    "testedTargets": 1,
                    "pass": 0,
                    "fail": 1,
                    "untested": 1,
                    "percentComplete": 0.5,
                },
                "lastTestedAtUtc": "2026-03-21T02:00:00Z",
                "eventSections": {
                    "system": {
                        "counts": {
                            "totalTargets": 1,
                            "testedTargets": 1,
                            "pass": 0,
                            "fail": 1,
                            "untested": 0,
                            "percentComplete": 1.0,
                        }
                    }
                },
                "devices": [{"deviceId": "1", "displayName": "Keypad", "counts": {"totalTargets": 1, "testedTargets": 1, "pass": 0, "fail": 1, "untested": 0, "percentComplete": 1.0}}],
            },
            "fails": [
                {
                    "targetKey": "btn:1:2:3:Lights",
                    "lastFailNote": "No voltage",
                    "deviceName": "Keypad",
                    "pageName": "Home",
                    "buttonName": "Lights",
                    "techName": "Alex",
                    "tag": "IN_PROGRESS",
                }
            ],
            "currentTargets": [
                {
                    "targetKey": "btn:1:2:3:Lights",
                    "targetName": "Lights",
                    "currentOutcome": "FAIL",
                    "techName": "Alex",
                }
            ],
            "history": [
                {
                    "testResultId": "r1",
                    "recordedAtUtc": "2026-03-21T02:00:00Z",
                    "outcome": "FAIL",
                    "failNote": "No voltage",
                    "source": "SINGLE",
                    "targetKey": "btn:1:2:3:Lights",
                    "techName": "Alex",
                }
            ],
            "testingTypes": {"types": [{"id": "button:Text", "label": "Text", "enabled": True}]},
            "technicianNames": ["Alex"],
        },
    )


class ReportPdfTest(unittest.TestCase):
    def test_closeout_pdf_omits_history_and_tokens(self):
        pdf = render_report_pdf(_sample_doc(preset=PRESET_CLOSEOUT))
        self.assertTrue(pdf.startswith(b"%PDF"))
        text = extract_pdf_text(pdf)
        self.assertIn("Cover", text)
        self.assertIn("Progress summary", text)
        self.assertIn("Device counts", text)
        self.assertIn("Fail detail", text)
        self.assertIn("No voltage", text)
        self.assertIn("Acme", text)
        self.assertNotIn("History", text)
        self.assertNotIn("Current targets", text)
        self.assertNotIn("Operator appendix", text)
        self.assertNotIn("Testing-type legend", text)
        self.assertNotIn("/testing/", text)
        self.assertNotIn("IN_PROGRESS", text)

    def test_full_audit_pdf_includes_history_structure(self):
        pdf = render_report_pdf(_sample_doc(preset=PRESET_FULL_AUDIT))
        text = extract_pdf_text(pdf)
        self.assertIn("Current targets", text)
        self.assertIn("History", text)
        self.assertIn("Testing-type legend", text)
        self.assertIn("SINGLE", text)
        self.assertNotIn("Operator appendix", text)

    def test_filename_uses_client_project_preset_date(self):
        doc = _sample_doc(preset=PRESET_CLOSEOUT)
        name = report_download_filename(doc, as_of="2026-03-21T15:04:00Z")
        self.assertEqual(name, "Acme-Job One-closeout-2026-03-21.pdf")


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed")
    return TestClient


class ReportApiTest(unittest.TestCase):
    def test_post_and_get_return_pdf_file(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        app = create_app(repo=repo)
        client = TestClient(app)
        c = client.post("/api/v1/commissioning/clients", json={"name": "Acme"}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": "Job One"},
        ).json()
        project_id = p["projectId"]
        posted = client.post(
            f"/api/v1/commissioning/projects/{project_id}/reports",
            json={"preset": "closeout"},
        )
        self.assertEqual(posted.status_code, 200, posted.text)
        self.assertIn("application/pdf", posted.headers.get("content-type", ""))
        disposition = posted.headers.get("content-disposition", "")
        self.assertIn(".pdf", disposition)
        self.assertRegex(disposition, re.compile(r"Acme-Job One-closeout-\d{4}-\d{2}-\d{2}\.pdf"))
        self.assertTrue(posted.content.startswith(b"%PDF"))
        text = extract_pdf_text(posted.content)
        self.assertIn("Cover", text)
        self.assertNotIn("History", text)

        got = client.get(f"/api/v1/commissioning/projects/{project_id}/reports?preset=closeout")
        self.assertEqual(got.status_code, 200, got.text)
        self.assertTrue(got.content.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
