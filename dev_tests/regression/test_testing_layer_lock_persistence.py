import unittest
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed") from exc
    return TestClient


class TestingLayerLockPersistenceTest(unittest.TestCase):
    def test_testing_layer_locks_persist_per_project_scope(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app

        app = create_app()
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Layer Lock Client"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Layer Lock Project"}).json()
        link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Tech"}).json()
        tech_token = str(link.get("techUrl") or "").split("/testing/")[1]

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            first = json.loads(ws.receive_text())
            self.assertEqual(first.get("type"), "testing_snapshot")
            self.assertEqual(first.get("layerLocks"), [])
            ws.send_text(
                json.dumps(
                    {
                        "type": "layer_lock.set",
                        "scopeKey": "project::device::page",
                        "layerKey": "layer-1",
                        "visible": False,
                        "locked": True,
                    }
                )
            )
            seen = None
            for _ in range(20):
                msg = json.loads(ws.receive_text())
                if msg.get("type") != "layer_lock_state":
                    continue
                seen = msg
                break
            self.assertIsNotNone(seen)
            self.assertEqual(seen.get("scopeKey"), "project::device::page")
            self.assertEqual(seen.get("layerKey"), "layer-1")
            self.assertEqual(seen.get("visible"), False)
            self.assertEqual(seen.get("locked"), True)

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws2:
            snap = json.loads(ws2.receive_text())
            self.assertEqual(snap.get("type"), "testing_snapshot")
            locks = list(snap.get("layerLocks") or [])
            self.assertEqual(len(locks), 1)
            self.assertEqual(locks[0].get("scopeKey"), "project::device::page")
            self.assertEqual(locks[0].get("layerKey"), "layer-1")
            self.assertEqual(locks[0].get("visible"), False)
            self.assertEqual(locks[0].get("locked"), True)


if __name__ == "__main__":
    unittest.main()
