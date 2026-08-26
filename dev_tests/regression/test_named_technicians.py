import json
import os
import tempfile
import unittest
from pathlib import Path
import sys


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


def _error_code(resp) -> str | None:
    body = resp.json()
    error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
    return (error or {}).get("code")


def _recv_until(ws, predicate, *, max_messages: int = 40):
    for _ in range(max_messages):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if not isinstance(msg, dict):
            continue
        if predicate(msg):
            return msg
    raise AssertionError("Did not receive expected websocket message.")


class NamedTechnicianHandoffTest(unittest.TestCase):
    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        return TestClient(app)

    def _job(self, client, *, client_name="Handoff Client", project_name="Handoff Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_named_tech_lives_under_company_not_anonymous_stub(self):
        from sentinel.server.services.commissioning_user import (
            COMMISSIONING_STUB_DISPLAY_NAME,
            COMMISSIONING_STUB_USER_ID,
        )

        client = self._app_client()
        listed = client.get("/api/v1/commissioning/technicians")
        self.assertEqual(listed.status_code, 200, listed.text)
        body = listed.json()
        self.assertEqual(body.get("companyId"), COMMISSIONING_STUB_USER_ID)
        self.assertEqual(body.get("companyName"), COMMISSIONING_STUB_DISPLAY_NAME)
        self.assertEqual(body.get("technicians"), [])

        created = client.post("/api/v1/commissioning/technicians", json={"name": "Alex"})
        self.assertEqual(created.status_code, 200, created.text)
        alex = created.json()
        self.assertTrue(alex.get("technicianId"))
        self.assertEqual(alex.get("name"), "Alex")
        self.assertEqual(alex.get("companyId"), COMMISSIONING_STUB_USER_ID)

        empty = client.post("/api/v1/commissioning/technicians", json={"name": "   "})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(_error_code(empty), "TECHNICIAN_NAME_REQUIRED")

        again = client.post("/api/v1/commissioning/technicians", json={"name": "alex"})
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json().get("technicianId"), alex["technicianId"])

        after = client.get("/api/v1/commissioning/technicians").json()
        names = [t.get("name") for t in after.get("technicians") or []]
        self.assertEqual(names, ["Alex"])

        _c, p = self._job(client)
        anonymous = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={})
        self.assertEqual(anonymous.status_code, 400)
        self.assertEqual(_error_code(anonymous), "TECHNICIAN_NAME_REQUIRED")

        blank = client.post(
            f"/api/v1/commissioning/projects/{p['projectId']}/tech-links",
            json={"label": "  "},
        )
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(_error_code(blank), "TECHNICIAN_NAME_REQUIRED")

        link = client.post(
            f"/api/v1/commissioning/projects/{p['projectId']}/tech-links",
            json={"technicianId": alex["technicianId"]},
        )
        self.assertEqual(link.status_code, 200, link.text)
        self.assertEqual(link.json().get("technicianId"), alex["technicianId"])
        self.assertEqual(link.json().get("name"), "Alex")
        self.assertEqual(link.json().get("label"), "Alex")

        links = client.get(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links").json()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get("technicianId"), alex["technicianId"])
        self.assertEqual(links[0].get("name"), "Alex")
        self.assertEqual(links[0].get("label"), "Alex")

    def test_named_tech_handoff_keeps_history_and_who(self):
        client = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]

        alex_link = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        morgan_link = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"label": "Morgan"},
        ).json()
        self.assertNotEqual(alex_link["technicianId"], morgan_link["technicianId"])
        self.assertNotEqual(alex_link["techLinkId"], morgan_link["techLinkId"])

        techs = client.get("/api/v1/commissioning/technicians").json()
        names = sorted(t.get("name") for t in techs.get("technicians") or [])
        self.assertEqual(names, ["Alex", "Morgan"])

        alex_token = str(alex_link["techUrl"]).split("/")[-1]
        morgan_token = str(morgan_link["techUrl"]).split("/")[-1]

        alex_pass = client.post(
            f"/api/v1/testing/{alex_token}/results",
            json={
                "outcome": "PASS",
                "target": {
                    "targetKey": "btn:1:2:3:Lights",
                    "kind": "BUTTON",
                    "targetName": "Lights",
                    "refs": {"deviceName": "Keypad"},
                },
            },
        )
        self.assertEqual(alex_pass.status_code, 200, alex_pass.text)
        alex_body = alex_pass.json()
        self.assertEqual(alex_body.get("source"), "SINGLE")
        self.assertIsNone(alex_body.get("batchId"))
        recorded = alex_body.get("recordedBy") or {}
        self.assertEqual(recorded.get("role"), "TECHNICIAN")
        self.assertEqual(recorded.get("techLinkId"), alex_link["techLinkId"])
        self.assertEqual(recorded.get("technicianId"), alex_link["technicianId"])
        self.assertEqual(recorded.get("name"), "Alex")
        self.assertEqual(alex_body.get("techName"), "Alex")

        morgan_fail = client.post(
            f"/api/v1/testing/{morgan_token}/results",
            json={
                "outcome": "FAIL",
                "failNote": "No voltage",
                "target": {
                    "targetKey": "btn:1:2:4:Shade",
                    "kind": "BUTTON",
                    "targetName": "Shade",
                    "refs": {"deviceName": "Keypad"},
                },
            },
        )
        self.assertEqual(morgan_fail.status_code, 200, morgan_fail.text)
        morgan_body = morgan_fail.json()
        self.assertEqual((morgan_body.get("recordedBy") or {}).get("name"), "Morgan")
        self.assertEqual(morgan_body.get("techName"), "Morgan")
        self.assertEqual((morgan_body.get("recordedBy") or {}).get("technicianId"), morgan_link["technicianId"])

        fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0].get("techName"), "Morgan")
        self.assertEqual((fails[0].get("recordedBy") or {}).get("name"), "Morgan")

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            snap = _recv_until(ws, lambda m: m.get("type") == "commissioning_snapshot")
        singles = [a for a in snap.get("activities") or [] if a.get("type") == "test_result"]
        by_key = {a.get("targetKey"): a for a in singles}
        self.assertEqual(by_key["btn:1:2:3:Lights"].get("techName"), "Alex")
        self.assertEqual((by_key["btn:1:2:3:Lights"].get("recordedBy") or {}).get("name"), "Alex")
        self.assertEqual(by_key["btn:1:2:4:Shade"].get("techName"), "Morgan")
        self.assertEqual((by_key["btn:1:2:4:Shade"].get("recordedBy") or {}).get("name"), "Morgan")

        same_alex = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        self.assertEqual(same_alex["technicianId"], alex_link["technicianId"])

    def test_group_pass_records_who_on_rows_and_snapshot_activity(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Group Who Client", project_name="Group Who Job")
        project_id = p["projectId"]
        link = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        token = str(link["techUrl"]).split("/")[-1]

        grouped = client.post(
            f"/api/v1/testing/{token}/results/batch",
            json={
                "outcome": "PASS",
                "targets": [
                    {"targetKey": "btn:1:2:3:One", "kind": "BUTTON", "targetName": "One", "refs": {"deviceName": "A"}},
                    {"targetKey": "btn:1:2:3:Two", "kind": "BUTTON", "targetName": "Two", "refs": {"deviceName": "A"}},
                ],
            },
        )
        self.assertEqual(grouped.status_code, 200, grouped.text)
        data = grouped.json()
        self.assertEqual(data.get("source"), "GROUP")
        self.assertTrue(data.get("batchId"))
        self.assertEqual(data.get("techName"), "Riley")
        self.assertEqual((data.get("recordedBy") or {}).get("name"), "Riley")
        self.assertEqual((data.get("recordedBy") or {}).get("technicianId"), link["technicianId"])
        self.assertTrue(data.get("results"))
        for row in data["results"]:
            self.assertEqual(row.get("source"), "GROUP")
            self.assertEqual(row.get("batchId"), data["batchId"])
            self.assertEqual((row.get("recordedBy") or {}).get("name"), "Riley")
            self.assertEqual(row.get("techName"), "Riley")

        walked = client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "outcome": "PASS",
                "target": {
                    "targetKey": "btn:9:9:9:Walked",
                    "kind": "BUTTON",
                    "targetName": "Walked",
                    "refs": {},
                },
            },
        ).json()
        self.assertEqual(walked.get("source"), "SINGLE")
        self.assertEqual(walked.get("techName"), "Riley")

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            snap = _recv_until(ws, lambda m: m.get("type") == "commissioning_snapshot")
        batch_acts = [a for a in snap.get("activities") or [] if a.get("type") == "test_results.batch"]
        single_acts = [a for a in snap.get("activities") or [] if a.get("type") == "test_result"]
        self.assertEqual(len(batch_acts), 1, snap.get("activities"))
        self.assertEqual(batch_acts[0].get("source"), "GROUP")
        self.assertEqual(batch_acts[0].get("batchId"), data["batchId"])
        self.assertEqual(batch_acts[0].get("techName"), "Riley")
        self.assertEqual((batch_acts[0].get("recordedBy") or {}).get("name"), "Riley")
        self.assertEqual((batch_acts[0].get("recordedBy") or {}).get("technicianId"), link["technicianId"])
        self.assertEqual(len(single_acts), 1)
        self.assertEqual(single_acts[0].get("techName"), "Riley")
        self.assertEqual(single_acts[0].get("source"), "SINGLE")

    def test_who_survives_reupload_and_handoff_the_next_day(self):
        TestClient = _require_fastapi()
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")

            def _regen_stub(*, projectId: str, apex_path: Path, phase_hook=None) -> dict:  # noqa: ARG001
                if callable(phase_hook):
                    phase_hook("extracting", 100)
                    phase_hook("generating", 100)
                out_dir = Path(td) / "generated" / projectId
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "Job_project_data.json").write_text(
                    '{"events":{"system":[],"driver":[]},"devices":[]}',
                    encoding="utf-8",
                )
                return {"projectId": projectId, "outDir": str(out_dir), "projectData": "stub"}

            original_regen = pipeline.regenerate_project
            pipeline.regenerate_project = _regen_stub  # type: ignore[assignment]
            try:
                from sentinel.server.app.main import create_app
                from sentinel.server.services.repositories import InMemoryRepository

                app = create_app(repo=InMemoryRepository())
                client = TestClient(app)
                _c, p = self._job(client, client_name="Regen Client", project_name="Regen Job")
                project_id = p["projectId"]
                alex = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/tech-links",
                    json={"name": "Alex"},
                ).json()
                alex_token = str(alex["techUrl"]).split("/")[-1]
                posted = client.post(
                    f"/api/v1/testing/{alex_token}/results",
                    json={
                        "outcome": "PASS",
                        "target": {
                            "targetKey": "event:1:Trigger",
                            "kind": "EVENT",
                            "targetName": "Trigger",
                            "refs": {"eventId": 1},
                        },
                    },
                )
                self.assertEqual(posted.status_code, 200, posted.text)

                up = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                    files={"apex": ("Job v2.apex", b"not-a-real-apex", "application/octet-stream")},
                )
                self.assertEqual(up.status_code, 200, up.text)

                morgan = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/tech-links",
                    json={"name": "Morgan"},
                ).json()
                morgan_token = str(morgan["techUrl"]).split("/")[-1]
                later = client.post(
                    f"/api/v1/testing/{morgan_token}/results",
                    json={
                        "outcome": "PASS",
                        "target": {
                            "targetKey": "event:2:Trigger",
                            "kind": "EVENT",
                            "targetName": "Trigger",
                            "refs": {"eventId": 2},
                        },
                    },
                )
                self.assertEqual(later.status_code, 200, later.text)

                with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
                    snap = _recv_until(ws, lambda m: m.get("type") == "commissioning_snapshot")
                singles = {
                    a.get("targetKey"): a
                    for a in (snap.get("activities") or [])
                    if a.get("type") == "test_result"
                }
                self.assertEqual(singles["event:1:Trigger"].get("techName"), "Alex")
                self.assertEqual(singles["event:2:Trigger"].get("techName"), "Morgan")
            finally:
                pipeline.regenerate_project = original_regen  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()
