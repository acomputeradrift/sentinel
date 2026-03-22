import json
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


def _recv_until(ws, predicate, *, max_messages: int = 10):
    for _ in range(max_messages):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if predicate(msg):
            return msg
    raise AssertionError("Did not receive expected websocket message.")


class CommissioningWsEventsTest(unittest.TestCase):
    def test_ws_emits_test_result_and_fail_tag_updated(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={"label": "Onsite"}).json()
        tech_token = tech["techUrl"].split("/testing/")[1]

        target_key = "btn:1:2:3:Button A"
        target = {"targetKey": target_key, "kind": "BUTTON", "targetName": "Button A", "refs": {"deviceName": "Device 1"}}

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            ok = client.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": target, "outcome": "PASS", "failNote": None},
            )
            self.assertEqual(ok.status_code, 200)

            msg1 = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("targetKey") == target_key)
            self.assertEqual(msg1.get("projectId"), project_id)
            self.assertEqual(msg1.get("outcome"), "PASS")

            set_tag = client.put(
                f"/api/v1/commissioning/projects/{project_id}/fail-tags",
                json={"targetKey": target_key, "tag": "IN_PROGRESS"},
            )
            self.assertEqual(set_tag.status_code, 200)

            msg2 = _recv_until(ws, lambda m: m.get("type") == "fail_tag_updated" and m.get("targetKey") == target_key)
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("tag"), "IN_PROGRESS")

