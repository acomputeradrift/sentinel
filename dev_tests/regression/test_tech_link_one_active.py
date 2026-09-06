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


class TechLinkOneActivePerNameTest(unittest.TestCase):
    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        return TestClient(app)

    def _job(self, client, *, client_name="One Active Client", project_name="One Active Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_create_same_name_twice_reuses_active_link_and_url(self):
        client = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]

        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        first_body = first.json()
        first_url = str(first_body.get("techUrl") or "")
        self.assertTrue(first_url.startswith("/testing/"), first_url)

        second = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "alex"},
        )
        self.assertEqual(second.status_code, 200, second.text)
        second_body = second.json()
        self.assertEqual(second_body["techLinkId"], first_body["techLinkId"])
        self.assertEqual(second_body["technicianId"], first_body["technicianId"])
        self.assertEqual(str(second_body.get("techUrl") or ""), first_url)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techLinkId"], first_body["techLinkId"])
        self.assertEqual(str(listed[0].get("techUrl") or ""), first_url)

        token = first_url.split("/testing/")[1]
        still_open = client.get(f"/testing/{token}")
        self.assertEqual(still_open.status_code, 200, still_open.text)

    def test_create_same_technician_id_reuses_without_rotate(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Reuse Id Client", project_name="Reuse Id Job")
        project_id = p["projectId"]

        tech = client.post("/api/v1/commissioning/technicians", json={"name": "Morgan"}).json()
        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"technicianId": tech["technicianId"]},
        ).json()
        second = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"technicianId": tech["technicianId"]},
        ).json()
        self.assertEqual(second["techLinkId"], first["techLinkId"])
        self.assertEqual(second["techUrl"], first["techUrl"])

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)

    def test_different_names_still_get_separate_active_links(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Two Names Client", project_name="Two Names Job")
        project_id = p["projectId"]

        alex = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        ).json()
        morgan = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Morgan"},
        ).json()
        self.assertNotEqual(alex["techLinkId"], morgan["techLinkId"])
        self.assertNotEqual(alex["techUrl"], morgan["techUrl"])

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 2)

    def test_reuse_after_revoke_issues_a_new_active_link(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="After Revoke Client", project_name="After Revoke Job")
        project_id = p["projectId"]

        first = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        old_url = first["techUrl"]
        client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{first['techLinkId']}/revoke"
        )

        again = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        self.assertTrue(str(again.get("techUrl") or "").startswith("/testing/"))
        self.assertNotEqual(again["techUrl"], old_url)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techUrl"], again["techUrl"])


if __name__ == "__main__":
    unittest.main()
