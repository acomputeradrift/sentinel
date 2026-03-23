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

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        target_key = "btn:1:2:3:Button A"

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            # Publish directly from inside the websocket portal thread so the
            # broker's asyncio queues are used from the correct event loop.
            broker = getattr(app.state, "project_event_broker", None)
            self.assertIsNotNone(broker)

            ws.portal.call(
                broker.publish,
                projectId=project_id,
                event={
                    "type": "test_result",
                    "projectId": project_id,
                    "recordedAtUtc": "2026-03-22T12:34:56.789123+00:00",
                    "targetKey": target_key,
                    "outcome": "PASS",
                    "targetName": "Button A",
                    "kind": "BUTTON",
                    "refs": {"deviceName": "Device 1"},
                },
            )

            msg1 = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("targetKey") == target_key)
            self.assertEqual(msg1.get("projectId"), project_id)
            self.assertEqual(msg1.get("outcome"), "PASS")
            self.assertEqual(msg1.get("recordedAtUtc"), "2026-03-22T12:34:56.789123+00:00")
            self.assertIsNone(msg1.get("failNote"))

            ws.portal.call(
                broker.publish,
                projectId=project_id,
                event={
                    "type": "test_result",
                    "projectId": project_id,
                    "recordedAtUtc": "2026-03-22T12:36:56.789123+00:00",
                    "targetKey": target_key,
                    "outcome": "FAIL",
                    "targetName": "Button A",
                    "kind": "BUTTON",
                    "refs": {"deviceName": "Device 1"},
                    "failNote": "Button not responding",
                },
            )

            msg1b = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("outcome") == "FAIL")
            self.assertEqual(msg1b.get("projectId"), project_id)
            self.assertEqual(msg1b.get("targetKey"), target_key)
            self.assertEqual(msg1b.get("recordedAtUtc"), "2026-03-22T12:36:56.789123+00:00")
            self.assertEqual(msg1b.get("failNote"), "Button not responding")

            ws.portal.call(
                broker.publish,
                projectId=project_id,
                event={
                    "type": "fail_tag_updated",
                    "projectId": project_id,
                    "recordedAtUtc": "2026-03-22T12:35:56.789123+00:00",
                    "targetKey": target_key,
                    "tag": "IN_PROGRESS",
                },
            )

            msg2 = _recv_until(ws, lambda m: m.get("type") == "fail_tag_updated" and m.get("targetKey") == target_key)
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("tag"), "IN_PROGRESS")

    def test_testing_ws_submits_and_receives_progress_rollups(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={}).json()
        tech_token = str(tech.get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token, "Expected tech token from techUrl.")

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit",
                        "target": {
                            "targetKey": "btn:1:2:3:Button A",
                            "targetName": "Button A",
                            "kind": "BUTTON",
                            "refs": {"deviceName": "Device 1"},
                        },
                        "outcome": "PASS",
                    }
                )
            )
            msg = _recv_until(ws, lambda m: m.get("type") in ("test_result", "test_result.recorded") and m.get("outcome") == "PASS")
            self.assertEqual(msg.get("projectId"), project_id)
            self.assertIn("progress", msg)
            self.assertIn("rollups", msg)

            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit",
                        "target": {
                            "targetKey": "btn:1:2:3:Button A",
                            "targetName": "Button A",
                            "kind": "BUTTON",
                            "refs": {"deviceName": "Device 1"},
                        },
                        "outcome": "FAIL",
                        "failNote": "Button not responding",
                    }
                )
            )
            msg2 = _recv_until(ws, lambda m: m.get("type") in ("test_result", "test_result.recorded") and m.get("outcome") == "FAIL")
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("failNote"), "Button not responding")
            self.assertIn("progress", msg2)
            self.assertIn("rollups", msg2)
