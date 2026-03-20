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


class ServerRoutesSmokeTest(unittest.TestCase):
    def test_commissioning_and_testing_flow(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app

        app = create_app()
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        self.assertIn("clientId", c)

        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        self.assertIn("projectId", p)
        self.assertEqual(p["clientId"], c["clientId"])

        link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
        self.assertIn("techLinkId", link)
        self.assertIn("techUrl", link)

        token = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links/{link['techLinkId']}/rotate").json()
        tech_url = token["techUrl"]
        self.assertTrue(tech_url.startswith("/testing/"))
        tech_token = tech_url.split("/testing/")[1]

        html = client.get(f"/testing/{tech_token}")
        self.assertEqual(html.status_code, 200)
        self.assertIn("text/html", html.headers.get("content-type", ""))

        fail = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={
                "target": {"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                "outcome": "FAIL",
                "failNote": "",
            },
        )
        self.assertEqual(fail.status_code, 400)
        self.assertEqual(fail.json()["error"]["code"], "FAIL_NOTE_REQUIRED")

        ok = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={
                "target": {"targetKey": "event:126:Trigger", "kind": "EVENT", "refs": {"eventId": 126}, "targetName": "Trigger"},
                "outcome": "PASS",
                "failNote": None,
            },
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["outcome"], "PASS")

        status = client.get(f"/api/v1/testing/{tech_token}/target-status", params={"targetKey": "event:126:Trigger"}).json()
        self.assertEqual(status["currentOutcome"], "PASS")

