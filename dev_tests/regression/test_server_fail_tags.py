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


class FailTagsTest(unittest.TestCase):
    def test_put_fail_tag_and_fails_includes_enriched_fields(self):
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

        target = {
            "targetKey": "btn:1:2:3:Button A",
            "kind": "BUTTON",
            "targetName": "Button A",
            "refs": {
                "deviceName": "Device 1",
                "pageName": "Page 2",
                "buttonName": "Button A",
                "scope": "DEVICE",
                "resolvedData": {"command": "do_something"},
            },
        }
        fail = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={"target": target, "outcome": "FAIL", "failNote": "No response"},
        )
        self.assertEqual(fail.status_code, 200)

        fails = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
        self.assertTrue(fails)
        row = fails[0]
        self.assertEqual(row["targetKey"], "btn:1:2:3:Button A")
        self.assertEqual(row["currentOutcome"], "FAIL")
        self.assertEqual(row["tag"], "NOT_STARTED")
        self.assertEqual(row["deviceName"], "Device 1")
        self.assertEqual(row["pageName"], "Page 2")
        self.assertEqual(row["buttonName"], "Button A")
        self.assertEqual(row["scope"], "DEVICE")
        self.assertEqual(row["targetName"], "Button A")
        self.assertEqual(row["resolvedData"], {"command": "do_something"})

        set_tag = client.put(
            f"/api/v1/commissioning/projects/{project_id}/fail-tags",
            json={"targetKey": "btn:1:2:3:Button A", "tag": "IN_PROGRESS"},
        )
        self.assertEqual(set_tag.status_code, 200)

        fails2 = client.get(f"/api/v1/commissioning/projects/{project_id}/fails").json()
        self.assertTrue(fails2)
        self.assertEqual(fails2[0]["tag"], "IN_PROGRESS")

    def test_put_fail_tag_sse_endpoint_is_removed(self):
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
        fail = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={"target": target, "outcome": "FAIL", "failNote": "No response"},
        )
        self.assertEqual(fail.status_code, 200)

        set_tag = client.put(
            f"/api/v1/commissioning/projects/{project_id}/fail-tags",
            json={"targetKey": target_key, "tag": "DONE"},
        )
        self.assertEqual(set_tag.status_code, 200)

        resp = client.get(f"/api/v1/commissioning/projects/{project_id}/events?once=1")
        self.assertEqual(resp.status_code, 410)
        body = resp.json()
        error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
        self.assertEqual((error or {}).get("code"), "SSE_REMOVED")
