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


def _error_code(resp) -> str | None:
    body = resp.json()
    error = (body.get("detail") or {}).get("error") if isinstance(body.get("detail"), dict) else body.get("error")
    return (error or {}).get("code")


class TechLinkPersistUrlTest(unittest.TestCase):
    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        return TestClient(app)

    def _job(self, client, *, client_name="Persist Client", project_name="Persist Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_create_then_list_returns_same_tech_url_without_rotating(self):
        client = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]

        created = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Alex"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        created_body = created.json()
        tech_url = str(created_body.get("techUrl") or "")
        self.assertTrue(tech_url.startswith("/testing/"), tech_url)
        tech_token = tech_url.split("/testing/")[1]
        self.assertTrue(tech_token)

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links")
        self.assertEqual(listed.status_code, 200, listed.text)
        links = listed.json()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["techLinkId"], created_body["techLinkId"])
        self.assertEqual(str(links[0].get("techUrl") or ""), tech_url)

        listed_again = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links")
        self.assertEqual(listed_again.status_code, 200, listed_again.text)
        links_again = listed_again.json()
        self.assertEqual(len(links_again), 1)
        self.assertEqual(str(links_again[0].get("techUrl") or ""), tech_url)
        self.assertEqual(links_again[0]["techLinkId"], created_body["techLinkId"])

        still_open = client.get(f"/testing/{tech_token}")
        self.assertEqual(still_open.status_code, 200, still_open.text)

        still_posts = client.post(
            f"/api/v1/testing/{tech_token}/results",
            json={
                "target": {
                    "targetKey": "event:1:Trigger",
                    "kind": "EVENT",
                    "refs": {"eventId": 1},
                    "targetName": "Trigger",
                },
                "outcome": "PASS",
                "failNote": None,
            },
        )
        self.assertEqual(still_posts.status_code, 200, still_posts.text)

    def test_rotate_revokes_old_url_and_lists_new_url(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Rotate Client", project_name="Rotate Job")
        project_id = p["projectId"]

        created = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Morgan"},
        ).json()
        old_url = str(created.get("techUrl") or "")
        old_token = old_url.split("/testing/")[1]
        tech_link_id = created["techLinkId"]

        rotated = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{tech_link_id}/rotate"
        )
        self.assertEqual(rotated.status_code, 200, rotated.text)
        new_url = str(rotated.json().get("techUrl") or "")
        self.assertTrue(new_url.startswith("/testing/"), new_url)
        self.assertNotEqual(new_url, old_url)
        new_token = new_url.split("/testing/")[1]

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["techLinkId"], tech_link_id)
        self.assertEqual(str(listed[0].get("techUrl") or ""), new_url)

        old_html = client.get(f"/testing/{old_token}")
        self.assertEqual(old_html.status_code, 410)
        self.assertEqual(_error_code(old_html), "TECH_LINK_REVOKED")

        new_html = client.get(f"/testing/{new_token}")
        self.assertEqual(new_html.status_code, 200, new_html.text)

    def test_revoke_returns_410_and_drops_link_from_active_list(self):
        client = self._app_client()
        _c, p = self._job(client, client_name="Revoke Client", project_name="Revoke Job")
        project_id = p["projectId"]

        created = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Riley"},
        ).json()
        tech_url = str(created.get("techUrl") or "")
        token = tech_url.split("/testing/")[1]
        tech_link_id = created["techLinkId"]

        revoked = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{tech_link_id}/revoke"
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertTrue(revoked.json().get("revoked"))

        listed = client.get(f"/api/v1/commissioning/projects/{project_id}/tech-links").json()
        self.assertEqual(listed, [])

        old_html = client.get(f"/testing/{token}")
        self.assertEqual(old_html.status_code, 410)
        self.assertEqual(_error_code(old_html), "TECH_LINK_REVOKED")


if __name__ == "__main__":
    unittest.main()
