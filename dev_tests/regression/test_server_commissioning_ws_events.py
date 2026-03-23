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
    def test_no_duplicate_commissioning_project_ws_route(self):
        _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())

        try:
            from starlette.routing import WebSocketRoute  # type: ignore
        except Exception:  # pragma: no cover
            raise unittest.SkipTest("starlette is not installed")

        ws_routes = [
            r
            for r in getattr(app.router, "routes", [])
            if isinstance(r, WebSocketRoute) and getattr(r, "path", None) == "/api/v1/commissioning/projects/{projectId}/ws"
        ]
        self.assertEqual(len(ws_routes), 1, "Expected exactly one commissioning project websocket route.")

    def test_ws_emits_test_result_and_fail_tag_updated(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)
        # Use a separate HTTP client while the websocket session is open to avoid
        # deadlocking on the TestClient portal/threading model.
        http = TestClient(app)

        c = http.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = http.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = http.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={"label": "Onsite"}).json()
        tech_token = tech["techUrl"].split("/testing/")[1]

        target_key = "btn:1:2:3:Button A"
        target = {"targetKey": target_key, "kind": "BUTTON", "targetName": "Button A", "refs": {"deviceName": "Device 1"}}

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            ok = http.post(
                f"/api/v1/testing/{tech_token}/results",
                json={"target": target, "outcome": "PASS", "failNote": None},
            )
            self.assertEqual(ok.status_code, 200)

            msg1 = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("targetKey") == target_key)
            self.assertEqual(msg1.get("projectId"), project_id)
            self.assertEqual(msg1.get("outcome"), "PASS")

            set_tag = http.put(
                f"/api/v1/commissioning/projects/{project_id}/fail-tags",
                json={"targetKey": target_key, "tag": "IN_PROGRESS"},
            )
            self.assertEqual(set_tag.status_code, 200)

            msg2 = _recv_until(ws, lambda m: m.get("type") == "fail_tag_updated" and m.get("targetKey") == target_key)
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("tag"), "IN_PROGRESS")
