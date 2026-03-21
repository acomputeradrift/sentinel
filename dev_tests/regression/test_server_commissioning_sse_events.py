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


class CommissioningSseEventsTest(unittest.TestCase):
    def test_sse_emits_on_test_result(self):
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

        ok = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={"target": {"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"}, "outcome": "PASS", "failNote": None},
        )
        self.assertEqual(ok.status_code, 200)

        with client.stream("GET", f"/api/v1/commissioning/projects/{project_id}/events?once=1") as resp:
            self.assertEqual(resp.status_code, 200)
            found = None
            for line in resp.iter_lines():
                s = (line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)).strip()
                if s.startswith("data:"):
                    payload = s[len("data:") :].strip()
                    import json

                    found = json.loads(payload)
                    break
            self.assertIsNotNone(found)
            self.assertEqual(found.get("type"), "test_result")
            self.assertEqual(found.get("projectId"), project_id)
            self.assertTrue(found.get("recordedAtUtc"))
            self.assertEqual(found.get("targetKey"), "event:126:Trigger")
            self.assertEqual(found.get("outcome"), "PASS")
            self.assertEqual(found.get("targetName"), "Trigger")
            self.assertEqual(found.get("kind"), "EVENT")
            self.assertEqual(found.get("refs"), {"eventId": 126})
