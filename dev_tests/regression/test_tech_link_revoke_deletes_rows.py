import os
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


class TechLinkRevokeDeletesRowsTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DATABASE_URL", None)

    def _app_client(self):
        TestClient = _require_fastapi()
        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        return TestClient(app), app

    def _job(self, client, *, client_name="Revoke Delete Client", project_name="Revoke Delete Job"):
        c = client.post("/api/v1/commissioning/clients", json={"name": client_name}).json()
        p = client.post(
            f"/api/v1/commissioning/clients/{c['clientId']}/projects",
            json={"name": project_name},
        ).json()
        return c, p

    def test_revoke_deletes_tech_link_and_token_rows(self):
        client, app = self._app_client()
        _c, p = self._job(client)
        project_id = p["projectId"]
        created = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Sung"},
        ).json()
        token = str(created["techUrl"]).split("/testing/")[1]
        tech_link_id = created["techLinkId"]

        revoked = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links/{tech_link_id}/revoke"
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertTrue(revoked.json().get("revoked"))

        repo = app.state.repo
        self.assertNotIn(tech_link_id, repo._tech_links)
        self.assertNotIn(token, repo._active_tokens)
        self.assertNotIn(tech_link_id, repo._active_token_by_link)
        self.assertEqual(repo.list_active_tech_links(projectId=project_id), [])
        self.assertEqual(client.get(f"/testing/{token}").status_code, 410)

    def test_forty_same_name_revoke_cycles_leave_no_dead_rows(self):
        client, app = self._app_client()
        _c, p = self._job(client, client_name="Sung Loop Client", project_name="Sung Loop Job")
        project_id = p["projectId"]
        last_token = ""
        for _ in range(40):
            created = client.post(
                f"/api/v1/commissioning/projects/{project_id}/tech-links",
                json={"name": "Sung"},
            ).json()
            last_token = str(created["techUrl"]).split("/testing/")[1]
            revoked = client.post(
                f"/api/v1/commissioning/projects/{project_id}/tech-links/{created['techLinkId']}/revoke"
            )
            self.assertEqual(revoked.status_code, 200, revoked.text)

        repo = app.state.repo
        leftover = [link for link in repo._tech_links.values() if link.projectId == project_id]
        self.assertEqual(leftover, [], leftover)
        self.assertEqual(repo.list_active_tech_links(projectId=project_id), [])
        self.assertEqual(client.get(f"/testing/{last_token}").status_code, 410)

        again = client.post(
            f"/api/v1/commissioning/projects/{project_id}/tech-links",
            json={"name": "Sung"},
        ).json()
        self.assertTrue(str(again.get("techUrl") or "").startswith("/testing/"))
        self.assertEqual(len(repo.list_active_tech_links(projectId=project_id)), 1)
        project_links = [link for link in repo._tech_links.values() if link.projectId == project_id]
        self.assertEqual(len(project_links), 1)

    def test_revoke_one_name_deletes_only_that_link_row(self):
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository

        repo = InMemoryRepository()
        client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="Isolate Delete Client")
        project = repo.create_project(
            userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="Isolate Delete Job"
        )
        sung, sung_token = repo.create_tech_link(projectId=project.projectId, label="Sung")
        alex, alex_token = repo.create_tech_link(projectId=project.projectId, label="Alex")
        repo.revoke_tech_link(projectId=project.projectId, techLinkId=sung.techLinkId)

        self.assertNotIn(sung.techLinkId, repo._tech_links)
        self.assertIn(alex.techLinkId, repo._tech_links)
        self.assertEqual(len(repo.list_active_tech_links(projectId=project.projectId)), 1)
        with self.assertRaises(KeyError):
            repo.resolve_active_token(techToken=sung_token.techToken)
        self.assertEqual(repo.resolve_active_token(techToken=alex_token.techToken).techLinkId, alex.techLinkId)


if __name__ == "__main__":
    unittest.main()
