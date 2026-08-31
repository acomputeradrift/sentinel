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


def _recv_until(ws, predicate, *, max_messages: int = 40):
    for _ in range(max_messages):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if not isinstance(msg, dict):
            continue
        if predicate(msg):
            return msg
    raise AssertionError("Did not receive expected websocket message.")


class TestingSnapshotRetestReadyTest(unittest.TestCase):
    def _client_and_token(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)
        c = client.post("/api/v1/commissioning/clients", json={"name": "Retest Client"}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Retest Project"}
        ).json()
        tech = client.post(
            f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}
        ).json()
        token = str(tech.get("techUrl") or "").split("/")[-1]
        return client, p["projectId"], token

    def test_fail_then_complete_sets_retest_ready_on_testing_snapshot(self):
        client, project_id, token = self._client_and_token()
        target = {
            "targetKey": "btn:1:2:3:Lights",
            "kind": "BUTTON",
            "targetName": "Lights",
            "refs": {"deviceName": "A"},
        }
        fail = client.post(
            f"/api/v1/testing/{token}/results",
            json={"target": target, "outcome": "FAIL", "failNote": "Dead"},
        )
        self.assertEqual(fail.status_code, 200, fail.text)

        tagged = client.put(
            f"/api/v1/commissioning/projects/{project_id}/fail-tags",
            json={"targetKey": "btn:1:2:3:Lights", "tag": "DONE"},
        )
        self.assertEqual(tagged.status_code, 200, tagged.text)

        with client.websocket_connect(f"/api/v1/testing/{token}/ws") as tech_ws:
            snap = _recv_until(tech_ws, lambda m: m.get("type") == "testing_snapshot")
        by_key = {str(r.get("targetKey") or ""): r for r in (snap.get("results") or [])}
        self.assertTrue(by_key["btn:1:2:3:Lights"].get("retestReady"))

    def test_fail_without_complete_is_not_retest_ready(self):
        client, _project_id, token = self._client_and_token()
        target = {
            "targetKey": "btn:1:2:3:Shade",
            "kind": "BUTTON",
            "targetName": "Shade",
            "refs": {},
        }
        fail = client.post(
            f"/api/v1/testing/{token}/results",
            json={"target": target, "outcome": "FAIL", "failNote": "Stuck"},
        )
        self.assertEqual(fail.status_code, 200, fail.text)

        with client.websocket_connect(f"/api/v1/testing/{token}/ws") as tech_ws:
            snap = _recv_until(tech_ws, lambda m: m.get("type") == "testing_snapshot")
        by_key = {str(r.get("targetKey") or ""): r for r in (snap.get("results") or [])}
        self.assertFalse(bool(by_key["btn:1:2:3:Shade"].get("retestReady")))

    def test_status_embed_defines_magenta_retest_trim(self):
        embed = (ROOT / "src" / "sentinel" / "ui" / "testing" / "sentinel_test_status_embed.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("retest:", embed)
        self.assertIn("#c026d3", embed)
        theme = (ROOT / "src" / "sentinel" / "ui" / "testing" / "sentinel_device_theme.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("--sentinel-trim-retest", theme)
        self.assertIn("#c026d3", theme)
