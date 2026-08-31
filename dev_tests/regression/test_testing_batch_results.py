import json
import time
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


def _recv_until(ws, predicate, *, max_messages: int = 40):
    for _ in range(max_messages):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if not isinstance(msg, dict):
            continue
        if predicate(msg):
            return msg
    raise AssertionError("Did not receive expected websocket message.")


class TestingBatchResultsTest(unittest.TestCase):
    def _client_and_token(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)
        c = client.post("/api/v1/commissioning/clients", json={"name": "Batch Client"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Batch Project"}).json()
        tech = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
        token = str(tech.get("techUrl") or "").split("/")[-1]
        return client, p["projectId"], token

    def test_http_batch_pass_records_all_targets(self):
        client, project_id, token = self._client_and_token()
        body = {
            "outcome": "PASS",
            "targets": [
                {"targetKey": "btn:1:2:3:Text", "kind": "BUTTON", "targetName": "Text", "refs": {"deviceName": "A"}},
                {"targetKey": "btn:1:2:3:Page Link", "kind": "BUTTON", "targetName": "Page Link", "refs": {"deviceName": "A"}},
                {"targetKey": "btn:1:2:3:Text", "kind": "BUTTON", "targetName": "Text", "refs": {"deviceName": "A"}},
            ],
        }
        resp = client.post(f"/api/v1/testing/{token}/results/batch", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["projectId"], project_id)
        self.assertEqual(data["outcome"], "PASS")
        self.assertEqual(data["count"], 2)
        keys = [row["targetKey"] for row in data["results"]]
        self.assertEqual(keys, ["btn:1:2:3:Text", "btn:1:2:3:Page Link"])
        self.assertTrue(data.get("batchId"))
        self.assertEqual(data.get("source"), "GROUP")
        batch_ids = {row.get("batchId") for row in data["results"]}
        self.assertEqual(batch_ids, {data["batchId"]})
        self.assertTrue(all(row.get("source") == "GROUP" for row in data["results"]))

        st = client.get(f"/api/v1/testing/{token}/target-status", params={"targetKey": "btn:1:2:3:Text"}).json()
        self.assertEqual(st["currentOutcome"], "PASS")

        single = client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "outcome": "PASS",
                "target": {"targetKey": "btn:9:9:9:Walked", "kind": "BUTTON", "targetName": "Walked", "refs": {}},
            },
        )
        self.assertEqual(single.status_code, 200, single.text)
        walked = single.json()
        self.assertEqual(walked.get("source"), "SINGLE")
        self.assertIsNone(walked.get("batchId"))
        self.assertNotEqual(walked.get("batchId"), data["batchId"])

    def test_http_batch_fail_requires_note(self):
        client, _project_id, token = self._client_and_token()
        resp = client.post(
            f"/api/v1/testing/{token}/results/batch",
            json={
                "outcome": "FAIL",
                "targets": [{"targetKey": "btn:1:2:3:Text", "kind": "BUTTON", "targetName": "Text", "refs": {}}],
            },
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
        self.assertEqual((error or {}).get("code"), "FAIL_NOTE_REQUIRED")

        ok = client.post(
            f"/api/v1/testing/{token}/results/batch",
            json={
                "outcome": "FAIL",
                "failNote": "Lights dead",
                "targets": [{"targetKey": "btn:1:2:3:Text", "kind": "BUTTON", "targetName": "Text", "refs": {}}],
            },
        )
        self.assertEqual(ok.status_code, 200, ok.text)

    def test_ws_batch_emits_one_event_then_rollups_and_reaches_console(self):
        client, project_id, token = self._client_and_token()
        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as commission_ws:
            _recv_until(commission_ws, lambda m: m.get("type") == "commissioning_snapshot")
            with client.websocket_connect(f"/api/v1/testing/{token}/ws") as tech_ws:
                tech_ws.send_text(
                    json.dumps(
                        {
                            "type": "test_result.submit_batch",
                            "outcome": "PASS",
                            "targets": [
                                {
                                    "targetKey": "btn:1:2:3:Text",
                                    "kind": "BUTTON",
                                    "targetName": "Text",
                                    "refs": {"deviceName": "Device 1", "pageName": "Home"},
                                },
                                {
                                    "targetKey": "event:9:Event Trigger",
                                    "kind": "EVENT",
                                    "targetName": "Event Trigger",
                                    "refs": {"eventId": 9, "eventKind": "SYSTEM"},
                                },
                            ],
                        }
                    )
                )
                tech_msg = _recv_until(tech_ws, lambda m: m.get("type") == "test_results.batch")
                self.assertEqual(tech_msg.get("projectId"), project_id)
                self.assertEqual(tech_msg.get("outcome"), "PASS")
                self.assertEqual(tech_msg.get("count"), 2)
                self.assertEqual(
                    tech_msg.get("targetKeys"),
                    ["btn:1:2:3:Text", "event:9:Event Trigger"],
                )
                self.assertTrue(tech_msg.get("batchId"))
                self.assertEqual(tech_msg.get("source"), "GROUP")
                self.assertNotIn("progress", tech_msg)
                self.assertIsInstance(tech_msg.get("seq"), int)

                commission_msg = _recv_until(commission_ws, lambda m: m.get("type") == "test_results.batch")
                self.assertEqual(commission_msg.get("count"), 2)
                self.assertEqual(commission_msg.get("targetKeys"), tech_msg.get("targetKeys"))
                self.assertEqual(commission_msg.get("batchId"), tech_msg.get("batchId"))
                self.assertEqual(commission_msg.get("source"), "GROUP")

                time.sleep(0.25)
                roll = _recv_until(tech_ws, lambda m: m.get("type") == "commissioning_rollups")
                self.assertIn("progress", roll)
                self.assertIn("rollups", roll)

    def test_snapshot_rebuild_keeps_group_pass_distinct_from_walked_singles(self):
        from sentinel.server.api.commissioning_snapshots import activities_from_latest, commissioning_snapshot
        from sentinel.server.services.repositories import TestResultRecord

        recs = {
            "btn:group:a": TestResultRecord(
                testResultId="10",
                projectId="p1",
                recordedAtUtc="2026-08-26T12:00:00+00:00",
                recordedBy={"role": "TECHNICIAN"},
                target={"targetKey": "btn:group:a", "kind": "BUTTON", "targetName": "A", "refs": {}},
                outcome="PASS",
                failNote=None,
                batchId="batch-aaa",
                source="GROUP",
            ),
            "btn:group:b": TestResultRecord(
                testResultId="11",
                projectId="p1",
                recordedAtUtc="2026-08-26T12:00:00+00:00",
                recordedBy={"role": "TECHNICIAN"},
                target={"targetKey": "btn:group:b", "kind": "BUTTON", "targetName": "B", "refs": {}},
                outcome="PASS",
                failNote=None,
                batchId="batch-aaa",
                source="GROUP",
            ),
            "btn:walked": TestResultRecord(
                testResultId="12",
                projectId="p1",
                recordedAtUtc="2026-08-26T12:01:00+00:00",
                recordedBy={"role": "TECHNICIAN"},
                target={"targetKey": "btn:walked", "kind": "BUTTON", "targetName": "Walked", "refs": {}},
                outcome="PASS",
                failNote=None,
                batchId=None,
                source="SINGLE",
            ),
        }
        acts = activities_from_latest(latest_results=recs)
        batch_acts = [a for a in acts if a.get("type") == "test_results.batch"]
        single_acts = [a for a in acts if a.get("type") == "test_result"]
        self.assertEqual(batch_acts, [])
        self.assertEqual(len(single_acts), 3)
        by_key = {a.get("targetKey"): a for a in single_acts}
        self.assertEqual(by_key["btn:group:a"]["targetName"], "A")
        self.assertEqual(by_key["btn:group:a"]["source"], "GROUP")
        self.assertEqual(by_key["btn:group:a"]["batchId"], "batch-aaa")
        self.assertEqual(by_key["btn:group:b"]["targetName"], "B")
        self.assertEqual(by_key["btn:group:b"]["source"], "GROUP")
        self.assertEqual(by_key["btn:group:b"]["batchId"], "batch-aaa")
        self.assertEqual(by_key["btn:walked"]["targetName"], "Walked")
        self.assertEqual(by_key["btn:walked"]["source"], "SINGLE")
        self.assertIsNone(by_key["btn:walked"].get("batchId"))

        client, project_id, token = self._client_and_token()
        walked = client.post(
            f"/api/v1/testing/{token}/results",
            json={
                "outcome": "PASS",
                "target": {"targetKey": "btn:walked:1", "kind": "BUTTON", "targetName": "Walked", "refs": {"deviceName": "A"}},
            },
        ).json()
        grouped = client.post(
            f"/api/v1/testing/{token}/results/batch",
            json={
                "outcome": "PASS",
                "targets": [
                    {"targetKey": "btn:group:1", "kind": "BUTTON", "targetName": "One", "refs": {"deviceName": "A"}},
                    {"targetKey": "btn:group:2", "kind": "BUTTON", "targetName": "Two", "refs": {"deviceName": "A"}},
                ],
            },
        ).json()
        self.assertEqual(walked.get("source"), "SINGLE")
        self.assertIsNone(walked.get("batchId"))
        self.assertEqual(grouped.get("source"), "GROUP")
        self.assertTrue(grouped.get("batchId"))

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as commission_ws:
            snap = _recv_until(commission_ws, lambda m: m.get("type") == "commissioning_snapshot")
        batch_acts = [a for a in snap.get("activities") or [] if a.get("type") == "test_results.batch"]
        single_acts = [a for a in snap.get("activities") or [] if a.get("type") == "test_result"]
        self.assertEqual(batch_acts, [], snap.get("activities"))
        self.assertEqual(len(single_acts), 3, snap.get("activities"))
        by_key = {a.get("targetKey"): a for a in single_acts}
        self.assertEqual(by_key["btn:group:1"].get("targetName"), "One")
        self.assertEqual(by_key["btn:group:1"].get("source"), "GROUP")
        self.assertEqual(by_key["btn:group:1"].get("batchId"), grouped["batchId"])
        self.assertEqual(by_key["btn:group:2"].get("targetName"), "Two")
        self.assertEqual(by_key["btn:group:2"].get("batchId"), grouped["batchId"])
        self.assertEqual(by_key["btn:walked:1"].get("targetKey"), "btn:walked:1")
        self.assertEqual(by_key["btn:walked:1"].get("source"), "SINGLE")

        with client.websocket_connect(f"/api/v1/testing/{token}/ws") as tech_ws:
            tech_snap = _recv_until(tech_ws, lambda m: m.get("type") == "testing_snapshot")
        by_key = {str(r.get("targetKey") or ""): r for r in (tech_snap.get("results") or [])}
        self.assertEqual(by_key["btn:group:1"].get("source"), "GROUP")
        self.assertEqual(by_key["btn:group:1"].get("batchId"), grouped["batchId"])
        self.assertEqual(by_key["btn:group:2"].get("batchId"), grouped["batchId"])
        self.assertEqual(by_key["btn:walked:1"].get("source"), "SINGLE")
        self.assertIsNone(by_key["btn:walked:1"].get("batchId"))

        rebuilt = commissioning_snapshot(repo=client.app.state.repo, projectId=project_id)
        rebuilt_batch = [a for a in rebuilt["activities"] if a.get("type") == "test_results.batch"]
        rebuilt_singles = [a for a in rebuilt["activities"] if a.get("type") == "test_result"]
        self.assertEqual(rebuilt_batch, [])
        self.assertEqual(len(rebuilt_singles), 3)
        rebuilt_by_key = {a.get("targetKey"): a for a in rebuilt_singles}
        self.assertEqual(rebuilt_by_key["btn:group:1"]["batchId"], grouped["batchId"])
        self.assertEqual(rebuilt_by_key["btn:group:1"]["source"], "GROUP")


if __name__ == "__main__":
    unittest.main()
