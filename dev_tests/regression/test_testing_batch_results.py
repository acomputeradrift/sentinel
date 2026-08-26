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

        st = client.get(f"/api/v1/testing/{token}/target-status", params={"targetKey": "btn:1:2:3:Text"}).json()
        self.assertEqual(st["currentOutcome"], "PASS")

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
                self.assertNotIn("progress", tech_msg)
                self.assertIsInstance(tech_msg.get("seq"), int)

                commission_msg = _recv_until(commission_ws, lambda m: m.get("type") == "test_results.batch")
                self.assertEqual(commission_msg.get("count"), 2)
                self.assertEqual(commission_msg.get("targetKeys"), tech_msg.get("targetKeys"))

                time.sleep(0.25)
                roll = _recv_until(tech_ws, lambda m: m.get("type") == "commissioning_rollups")
                self.assertIn("progress", roll)
                self.assertIn("rollups", roll)


if __name__ == "__main__":
    unittest.main()
